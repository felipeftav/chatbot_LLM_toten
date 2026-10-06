"""Serviço de respostas pré-programadas (FAQ) e áudios gravados."""

import base64
from typing import Optional, Tuple
from src.config import STATIC_DIR

EVENT_INFO = {
    "Onde posso ver os projetos de Ciência de Dados para Negócios?": {
        "text": "Os projetos de Ciência de Dados para Negócios estão no 3º andar, sala 307! 💡 Lá, os alunos mostram soluções inovadoras e é onde você encontra a LIA — eu! 🤖",
        "audio_path": "audio/respostas_pre_gravadas/projetos_cdn.mp3",
    },
    "E os trabalhos de Marketing, onde estão?": {
        "text": "Os projetos de Marketing estão no 2º andar, nas salas 202, 203, 206, 208, 209, 210 e também na área do ping pong. 🎯 Uma mostra cheia de criatividade e estratégia!",
        "audio_path": "audio/respostas_pre_gravadas/projetos_mkt.mp3",
    },
    "Onde encontro os projetos de GNI?": {
        "text": "Os projetos de Gestão de Negócios e Inovação (GNI) estão espalhados pelo térreo, 2º e 3º andares. 💼 No térreo há a Feira de Empreendedores, e nos outros andares, os projetos acadêmicos e especiais!",
        "audio_path": "audio/respostas_pre_gravadas/projetos_gni.mp3",
    },
    "Onde encontro comidas e doces?": {
        "text": "A área de alimentação fica no térreo! 🍔🍰 Você encontra Tati Nasi Confeitaria, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom e Cantina das Bentas. Delícias feitas por empreendedores da feira!",
        "audio_path": "audio/respostas_pre_gravadas/empresas_alimentacao.mp3",
    },
    "Quais empresas estão no evento?": {
        "text": "No térreo estão várias empresas e parceiros incríveis! 🌟 Como Tati Nasi, Bolindos, Nabru Doces, ZAP Burger, Sorveteria Cris Bom, Cantina das Bentas, Dans Brechó, Anainá Moda Sustentável e muitas outras!",
        "audio_path": "audio/respostas_pre_gravadas/empresas_expondo.mp3",
    },
    "O que é a LIA?": {
        "text": "Sou eu! 😄 Fui criada pelos alunos do 2º semestre de Ciência de Dados para Negócios — Felipe Tavares, Thiago Teles, Paulo Futagawa, Thais Nakazone e Riquelme Nichiyama — com orientação dos profs. Rômulo Maia e Nathane de Castro. Minha missão é ajudar você no Meta Day! 💙🤖",
        "audio_path": "audio/respostas_pre_gravadas/o_que_e_lia.mp3",
    },
}


def get_faq_match(user_message: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Verifica se a mensagem do usuário corresponde exatamente ou de forma normalizada
    a uma das perguntas frequentes cadastradas.
    Retorna uma tupla (texto_resposta, audio_base64) se encontrado, ou None.
    """
    msg_limpa = user_message.strip()
    faq_data = EVENT_INFO.get(msg_limpa)

    if not faq_data:
        # Tenta busca flexível ignorando pontuação básica ou case
        msg_lower = msg_limpa.lower().rstrip("?!. ")
        for pergunta, dados in EVENT_INFO.items():
            if pergunta.lower().rstrip("?!. ") == msg_lower:
                faq_data = dados
                break

    if not faq_data:
        return None

    reply_text = faq_data["text"]
    audio_path = faq_data.get("audio_path")
    audio_base64 = None

    if audio_path:
        full_audio_path = STATIC_DIR / audio_path
        if full_audio_path.exists():
            try:
                with open(full_audio_path, "rb") as f:
                    audio_base64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                print(f"⚠️ Erro ao ler áudio pré-gravado ({audio_path}): {e}")

    return reply_text, audio_base64
