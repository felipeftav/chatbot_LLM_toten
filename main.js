// script.js
marked.setOptions({ breaks: true });
new window.VLibras.Widget('https://vlibras.gov.br/app');

// --- Constantes dos Elementos da UI ---
const messageInput = document.getElementById('message-input');
const chatMessages = document.getElementById('chat-messages');
const micButton = document.getElementById('mic-button');
const summarizeButton = document.getElementById('summarize-button');
const suggestTopicButton = document.getElementById('suggest-topic-button');
const sendTextButton = document.getElementById('send-text-button');
const ttsButton = document.getElementById('toggle-tts-button');
const avatarImage = document.getElementById('avatar-image');
const restartButton = document.getElementById('restart-button');
const presetButtonsContainer = document.getElementById('preset-buttons-container');

const splashScreen = document.getElementById('splash-screen');
const mainContainer = document.getElementById('main-container');
const startForm = document.getElementById('start-form');
const nameInput = document.getElementById('name-input');

// Configuração da URL do Backend (correta para ambiente local e Render)
const backendUrl = `${window.location.origin}/chat`;    

// --- CORREÇÃO 1: Armazenar o perfil do usuário no frontend ---
// Esta variável guardará os dados do formulário após o login.
let userProfile = {};

// LÓGICA DO TIMER DE INATIVIDADE
let inactivityTimer;
const inactivityTimeout = 90000; 

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
        console.log("Usuário inativo. Voltando para a tela inicial.");
        window.location.reload();
    }, inactivityTimeout);
}

// // --- LÓGICA DA TELA INICIAL (AGORA SALVA O PERFIL LOCALMENTE) ---
// startForm.addEventListener('submit', (e) => {
//     e.preventDefault();
    
//     const name = nameInput.value.trim();
//     const role = document.getElementById('role-select').value;
//     const interestArea = document.getElementById('interest-area-select').value;
//     const objective = document.getElementById('objective-select').value;

//     if (name) {
//         // Preenche a variável userProfile com os dados do formulário
//         userProfile = {
//             name,
//             role,
//             interestArea,
//             objective,
//         };

//         // A chamada fetch para "/save-form" foi removida, pois não é mais necessária.
//         // Os dados do perfil serão enviados com cada mensagem.

//         // Lógica de transição de tela
//         splashScreen.style.display = 'none';
//         mainContainer.style.display = 'flex';
        
//         const welcomeMessage = `Olá, <strong>${name}</strong>! 👋<br>Que legal que um(a) <strong>${role}</strong> com interesse em <strong>${interestArea}</strong> veio nos visitar! Estou pronta para te ajudar a <strong>${objective}</strong>. Sobre o que quer saber primeiro?`;
//         appendMessage('bot', welcomeMessage);

//         resetInactivityTimer();
//         window.addEventListener('mousemove', resetInactivityTimer);
//         window.addEventListener('keydown', resetInactivityTimer);
//         window.addEventListener('click', resetInactivityTimer);
//         window.addEventListener('scroll', resetInactivityTimer, true);
//     }
// });

// --- LÓGICA DA TELA INICIAL (COM LOADING DE ÁUDIO) ---
startForm.addEventListener('submit', async (e) => { // <-- 1. Adicionado 'async'
    e.preventDefault();
    
    const name = nameInput.value.trim();
    const role = document.getElementById('role-select').value;
    const interestArea = document.getElementById('interest-area-select').value;
    const objective = document.getElementById('objective-select').value;
    const sessionId = crypto.randomUUID();

    if (name) {
        // --- 1. Lista de pessoas importantes ---
        const specialGuests = {
            "clovis dias": "o presidente do Centro Paula Souza",
            "maycon geres": "o vice-presidente do Centro Paula Souza.",
            "robson dos santos": "o coordenador geral de Ensino Superior de Graduação do Centro Paula Souza",
            "divanil antunes urbano": "o coordenador geral de Ensino Médio e Técnico do Centro Paula Souza",
            "paulo marcelo tavares ribeiro": "o gerente da Unidade de Cultura Empreendedora do Sebrae-SP",
            "andré velasques de oliveira": "o coordenador da Assessoria de Comunicação do Centro Paula Souza",
            "marcos antonio maia lavio de oliveira": "o coordenador da Fatec Itapevi",
            "paulo hélio kanayama": "o coordenador da Fatec Franco da Rocha",
            "marta da silva": "a chefe da Divisão Educacional Regional 5",
            "nelson hervey costa": "o diretor superintendente do Sebrae São Paulo",
            "marco vinholi": "o diretor técnico do Sebrae São Paulo.",
            "reinaldo pedro corrêa": "o diretor de administração e finanças do Sebrae São Paulo"
        };

        // --- 2. Função auxiliar para normalizar o nome ---
        function normalize(str) {
            return str
                .normalize("NFD") // remove acentos
                .replace(/[\u0300-\u036f]/g, "")
                .toLowerCase()
                .trim();
        }

        const normalizedInput = normalize(name);
        let matchedGuest = null;

        // --- 3. Verifica se o nome digitado corresponde a algum da lista ---
        for (const guestName in specialGuests) {
            const normalizedGuest = normalize(guestName);

            // Divide os nomes em palavras
            const inputWords = normalizedInput.split(/\s+/);
            const guestWords = normalizedGuest.split(/\s+/);

            // Conta quantas palavras coincidem
            const matchedWords = inputWords.filter(word => guestWords.includes(word)).length;

            // Exige pelo menos 2 palavras coincidentes ou igualdade total
            if (matchedWords >= 2 || normalizedInput === normalizedGuest) {
                matchedGuest = guestName;
                break;
            }
        }

        // --- 4. Monta o perfil do usuário ---
        userProfile = {
            name,
            role,
            interestArea,
            objective,
            sessionId,
        };

        // --- 5. Lógica de transição de tela ---
        splashScreen.style.display = 'none';
        mainContainer.style.display = 'flex';

        let welcomeMessageHTML, welcomeMessageText;

        if (matchedGuest) {
            // Mensagem personalizada para convidados especiais
            const description = specialGuests[matchedGuest];
            welcomeMessageHTML = `Seja muito bem-vindo(a), <strong>${name}</strong>! 👏<br>É uma honra receber <strong>${description}</strong> neste evento!<br> Em que posso te ajudar?`;
            welcomeMessageText = `Seja muito bem-vindo, ${name}! É uma honra receber ${description} neste evento! Em que posso te ajudar?`;
        } else {
            // Mensagem padrão
            welcomeMessageHTML = `Olá, <strong>${name}</strong>! 👋<br>Que legal que um(a) <strong>${role}</strong> com interesse em <strong>${interestArea}</strong> veio nos visitar! Estou pronta para te ajudar a <strong>${objective}</strong>. Sobre o que quer saber primeiro?`;
            welcomeMessageText = `Olá, ${name}! Que legal que um ${role} com interesse em ${interestArea} veio nos visitar! Estou pronta para te ajudar a ${objective}. Sobre o que quer saber primeiro?`;
        }

        // --- 6. Mostra indicador e toca áudio ---
        showTypingIndicator();
        const audioData = await fetchWelcomeAudio(welcomeMessageText);
        removeTypingIndicator();
        appendMessage('bot', welcomeMessageHTML);
        playAudioFromData(audioData);

        // --- 7. Continua lógica normal ---
        resetInactivityTimer();
        window.addEventListener('mousemove', resetInactivityTimer);
        window.addEventListener('keydown', resetInactivityTimer);
        window.addEventListener('click', resetInactivityTimer);
        window.addEventListener('scroll', resetInactivityTimer, true);
    }

});

messageInput.addEventListener('keydown', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendTextButton.click();
    }
});

// --- LÓGICA DE ANIMAÇÃO DO AVATAR ---
let mouthAnimationInterval;
const avatar_boca_fechada = './assets/avatar_fechada.webp';
const avatar_boca_aberta = './assets/avatar_aberta.webp';

// Pré-carregar imagens para evitar lag no início
const imgFechada = new Image();
const imgAberta = new Image();
imgFechada.src = avatar_boca_fechada;
imgAberta.src = avatar_boca_aberta;

function startTalkingAnimation() {
    stopTalkingAnimation(); 
    let isMouthOpen = false;

    mouthAnimationInterval = setInterval(() => {
        avatarImage.src = isMouthOpen ? imgFechada.src : imgAberta.src;
        isMouthOpen = !isMouthOpen;
    }, 250);
}

function stopTalkingAnimation() {
    if (mouthAnimationInterval) {
        clearInterval(mouthAnimationInterval);
        mouthAnimationInterval = null;
    }
    avatarImage.src = imgFechada.src;
}


async function fetchWelcomeAudio(text) {
    // Se o TTS estiver desligado, retorna nulo imediatamente.
    if (!isTtsEnabled) return null;

    try {
        const response = await fetch('/get-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        
        // Retorna os dados do áudio (ou undefined se não vier)
        return data.audioData; 

    } catch (error) {
        console.error('Erro ao buscar áudio de boas-vindas:', error);
        // Retorna nulo em caso de erro
        return null; 
    }
}



// --- LÓGICA DE GRAVAÇÃO DE VOZ ---
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
micButton.addEventListener('click', async () => {
    if (isRecording) {
        mediaRecorder.stop();
    } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();
            isRecording = true;
            audioChunks = [];
            micButton.classList.add('recording', 'bg-red-700');
            micButton.classList.remove('bg-red-500');
            messageInput.placeholder = "Gravando... Clique para parar.";
            setUiDisabled(true, true);
            mediaRecorder.addEventListener("dataavailable", event => { audioChunks.push(event.data); });
            mediaRecorder.addEventListener("stop", () => {
                isRecording = false;
                micButton.classList.remove('recording', 'bg-red-700');
                micButton.classList.add('bg-red-500');
                messageInput.placeholder = "Digite sua mensagem aqui...";
                setUiDisabled(false);
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                sendAudioToServer(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            });
        } catch (err) {
            console.error("Erro ao acessar o microfone:", err);
            alert("Não foi possível acessar o microfone. Verifique as permissões.");
        }
    }
});

// --- LÓGICA DE SUBMISSÃO (Texto, Áudio e Botões Pré-programados) ---
document.getElementById('chat-form').addEventListener('submit', handleTextSubmit);
sendTextButton.addEventListener('click', handleTextSubmit);

presetButtonsContainer.addEventListener('click', (e) => {
    if (e.target.classList.contains('preset-button')) {
        const question = e.target.textContent;
        handlePresetClick(question);
    }
});

async function handleTextSubmit(e) {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (!message) return;
    appendMessage('user', message);
    messageInput.value = '';
    if(presetButtonsContainer) presetButtonsContainer.style.display = 'none';
    await fetchBotReply({ message: message });
}

async function handlePresetClick(question) {
    appendMessage('user', question);
    if(presetButtonsContainer) presetButtonsContainer.style.display = 'none';
    await fetchBotReply({ message: question, isPreset: true });
}

async function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'user_audio.webm');
    
    // --- LINHA ADICIONADA ---
    // Anexa o perfil do usuário como uma string JSON.
    formData.append("profile", JSON.stringify(userProfile));

    appendMessage('user', '<i>Mensagem de voz enviada...</i>');
    if(presetButtonsContainer) presetButtonsContainer.style.display = 'none';
    await fetchBotReply({ body: formData, isAudio: true });
}

async function fetchBotReply(payload) {
    setUiDisabled(true);
    showTypingIndicator();
    try {
        let requestOptions;
        if (payload.isAudio) {
            requestOptions = { method: 'POST', body: payload.body };
        } else {
            const body = payload.isPreset 
                ? { preset_question: payload.message, tts_enabled: isTtsEnabled } 
                : { message: payload.message, tts_enabled: isTtsEnabled };

            // --- CORREÇÃO 2: Enviar o perfil junto com cada requisição ---
            // Adicionamos o objeto 'userProfile' ao corpo (body) da requisição.
            body.profile = userProfile;

            requestOptions = { 
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(body) 
            };
        }
        
        const response = await fetch(backendUrl, requestOptions);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        
        removeTypingIndicator();
        appendMessage('bot', data.reply);
        playAudioFromData(data.audioData);

    } catch (error) {
        handleFetchError(error);
    } finally {
        setUiDisabled(false);
        messageInput.focus();
        if (presetButtonsContainer) {
            presetButtonsContainer.style.display = 'block'; 
        }
    }
}

// --- LÓGICA: RESUMIR E SUGERIR ---
summarizeButton.addEventListener('click', async () => {
    showTypingIndicator(); setUiDisabled(true);
    try {
        // CORREÇÃO: Adiciona headers e o body com o userProfile
        const response = await fetch(`${backendUrl.replace('/chat', '/summarize')}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ profile: userProfile }) 
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        // ... resto do código
        const data = await response.json();
        if (data.summary) { appendSystemMessage(data.summary); } 
        else if (data.error) { appendSystemMessage(`<strong>Erro:</strong> ${data.error}`); }
    } catch (error) {
        console.error('Erro ao resumir conversa:', error);
        appendSystemMessage('<strong>Erro:</strong> Não foi possível conectar ao servidor para resumir.');
    } finally { removeTypingIndicator(); setUiDisabled(false); }
});

suggestTopicButton.addEventListener('click', async () => {
    const originalPlaceholder = messageInput.placeholder;
    messageInput.placeholder = "Buscando uma ideia..."; setUiDisabled(true);
    try {
        const response = await fetch(`${backendUrl.replace('/chat', '/suggest-topic')}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();
        if (data.topic) { messageInput.value = data.topic; messageInput.focus(); } 
        else { messageInput.placeholder = "Erro ao sugerir. Tente novamente."; setTimeout(() => { messageInput.placeholder = originalPlaceholder; }, 2000); }
    } catch (error) {
        console.error('Erro ao sugerir tópico:', error);
        messageInput.placeholder = "Erro de conexão."; setTimeout(() => { messageInput.placeholder = originalPlaceholder; }, 2000);
    } finally { setUiDisabled(false); if (!messageInput.value) { messageInput.placeholder = originalPlaceholder; } }
});

// --- LÓGICA: REINICIAR CONVERSA ---
restartButton.addEventListener('click', async () => {
    try {
        // CORREÇÃO: Adiciona headers e o body com o userProfile
        await fetch(`${backendUrl.replace('/chat', '/restart')}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ profile: userProfile }) 
        });
        
        // Agora o reload faz sentido, pois o backend limpou a sessão
        window.location.reload(); 
        
    } catch (error) {
        console.error('Erro ao reiniciar a conversa:', error);
        appendSystemMessage('<strong>Erro:</strong> Não foi possível conectar ao servidor para reiniciar a conversa.');
    }
});

// --- FUNÇÕES AUXILIARES DA UI ---
function setUiDisabled(isDisabled, recording = false) { messageInput.disabled = isDisabled; sendTextButton.disabled = isDisabled; suggestTopicButton.disabled = isDisabled; summarizeButton.disabled = isDisabled; micButton.disabled = isDisabled && !recording; }
function handleFetchError(error) { console.error('Erro de comunicação com o backend:', error); removeTypingIndicator(); appendMessage('bot', 'Desculpe, ocorreu um erro de conexão.'); }

function appendMessage(sender, message) {
    const wrapper = document.createElement('div');
    wrapper.classList.add('flex', 'mb-6');

    const bubble = document.createElement('div');
    bubble.classList.add('p-4', 'rounded-2xl', 'max-w-lg', 'text-lg');

    if (sender === 'bot') {
        wrapper.classList.add('justify-start');
        bubble.classList.add('bg-slate-800', 'text-white', 'rounded-bl-none');
        bubble.innerHTML = marked.parse(message);
    } else {
        wrapper.classList.add('justify-end');
        bubble.classList.add('bg-slate-200', 'text-slate-800', 'rounded-br-none');
        bubble.innerHTML = message;
    }

    wrapper.appendChild(bubble);
    chatMessages.appendChild(wrapper);

    if (typeof MathJax !== "undefined" && sender === 'bot') {
        MathJax.typesetPromise([wrapper]).catch((err) => console.log('Erro MathJax:', err));
    }
}

// 🔁 Observa mudanças no chat e rola automaticamente até o final
const observer = new MutationObserver(() => {
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: "smooth"
    });
});
observer.observe(chatMessages, { childList: true, subtree: true });

function appendSystemMessage(message) {
    const wrapper = document.createElement('div'); wrapper.classList.add('flex', 'justify-center', 'my-4', 'mx-2');
    const bubble = document.createElement('div'); bubble.classList.add('bg-slate-600', 'text-white', 'p-3', 'rounded-xl', 'max-w-xl', 'text-base', 'italic');
    bubble.innerHTML = `✨ **Resumo da Conversa:**<br>${marked.parse(message)}`; wrapper.appendChild(bubble); chatMessages.appendChild(wrapper);
    if (typeof MathJax !== "undefined") { MathJax.typesetPromise([wrapper]).catch((err) => console.log('Erro MathJax:', err)); }
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
const showTypingIndicator=()=>{const t=document.createElement('div');t.id='typing-indicator';t.classList.add('flex','justify-start','mb-6');t.innerHTML=`<div class="bg-slate-800 text-white p-4 rounded-2xl rounded-bl-none"><div class="flex items-center space-x-1"><span class="w-2 h-2 bg-white rounded-full animate-bounce" style="animation-delay:0s"></span><span class="w-2 h-2 bg-white rounded-full animate-bounce" style="animation-delay:0.2s"></span><span class="w-2 h-2 bg-white rounded-full animate-bounce" style="animation-delay:0.4s"></span></div></div>`;chatMessages.appendChild(t);chatMessages.scrollTop=chatMessages.scrollHeight};
const removeTypingIndicator=()=>{const t=document.getElementById('typing-indicator');if(t){t.remove()}};

// --- Lógica de TTS ---
let isTtsEnabled=true;let currentAudio=null;const iconSoundOn=`<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`;const iconSoundOff=`<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/></svg>`;
function base64ToArrayBuffer(b){const s=window.atob(b);const l=s.length;const B=new Uint8Array(l);for(let i=0;i<l;i++){B[i]=s.charCodeAt(i)}return B.buffer}
function pcmToWavBlob(d){const r=24000;const p=base64ToArrayBuffer(d);const D=new Int16Array(p);const h=new ArrayBuffer(44);const v=new DataView(h);v.setUint32(0,1380533830,false);v.setUint32(4,36+D.byteLength,true);v.setUint32(8,1463899717,false);v.setUint32(12,1718449184,false);v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,r,true);v.setUint32(28,r*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);v.setUint32(36,1684108385,false);v.setUint32(40,D.byteLength,true);return new Blob([h,D],{type:'audio/wav'})}

const playAudioFromData=(d)=>{if(currentAudio){currentAudio.pause()}stopTalkingAnimation();if(!isTtsEnabled||!d)return;try{const b=pcmToWavBlob(d);const u=URL.createObjectURL(b);currentAudio=new Audio(u);currentAudio.addEventListener('play',startTalkingAnimation);currentAudio.addEventListener('ended',stopTalkingAnimation);currentAudio.addEventListener('pause',stopTalkingAnimation);currentAudio.addEventListener('error',stopTalkingAnimation);currentAudio.play()}catch(e){console.error("Erro ao tocar áudio:",e)}};
const updateTtsButtonIcon=()=>{ttsButton.innerHTML=isTtsEnabled?iconSoundOn:iconSoundOff};
ttsButton.addEventListener('click',()=>{isTtsEnabled=!isTtsEnabled;updateTtsButtonIcon();if(!isTtsEnabled&&currentAudio){currentAudio.pause()}});
updateTtsButtonIcon();

document.addEventListener('DOMContentLoaded', () => {
    
    // --- LÓGICA UNIVERSAL PARA POSICIONAR TOOLTIPS ---
    // Esta função centraliza a lógica para não repetir código
    const positionTooltip = (tooltipElement, mouseEvent) => {
        // Remove 'hidden' para calcular as dimensões
        tooltipElement.classList.remove('hidden');
        
        const tooltipHeight = tooltipElement.offsetHeight;
        const tooltipWidth = tooltipElement.offsetWidth;
        const margin = 15; // Espaço do cursor

        let top, left;

        // Lógica Y (Cima/Baixo)
        if (mouseEvent.clientY > window.innerHeight / 2) {
            // Mouse na metade de baixo -> Tooltip para CIMA
            top = mouseEvent.pageY - tooltipHeight - margin;
        } else {
            // Mouse na metade de cima -> Tooltip para BAIXO
            top = mouseEvent.pageY + margin;
        }

        // Lógica X (Esquerda/Direita)
        // Começa centralizado
        left = mouseEvent.pageX - (tooltipWidth / 2);

        // Ajusta se sair pela esquerda
        if (left < margin) {
            left = margin;
        }
        // Ajusta se sair pela direita
        if (left + tooltipWidth + margin > window.innerWidth) {
            left = window.innerWidth - tooltipWidth - margin;
        }
        
        // Aplica as posições
        tooltipElement.style.top = top + 'px';
        tooltipElement.style.left = left + 'px';
    };

    // =================================================
    //  TOOLTIP DA LGPD (COM LÓGICA INTELIGENTE)
    // =================================================
    const lgpdLink = document.getElementById('lgpd-info');
    
    const tooltip = document.createElement('div');
    tooltip.id = 'lgpd-tooltip';
    tooltip.className = 'hidden absolute bg-white border border-slate-300 p-3 rounded-xl shadow-lg max-w-xs text-sm text-slate-700 z-50';
    tooltip.innerHTML = `
        <strong>Resumo da LGPD:</strong><br>
        A Lei Geral de Proteção de Dados (Lei nº 13.709/2018) garante que seus dados pessoais
        só sejam usados com o seu consentimento e para finalidades legítimas, como melhorar sua
        experiência neste evento. Nenhuma informação é compartilhada sem autorização.
    `;
    document.body.appendChild(tooltip);

    // Eventos do tooltip da LGPD
    lgpdLink.addEventListener('mouseenter', (e) => {
        positionTooltip(tooltip, e); // Usa a nova função!
    });
    lgpdLink.addEventListener('mouseleave', () => {
        tooltip.classList.add('hidden');
    });

    // =================================================
    //  TOOLTIP DOS DEVS (COM LÓGICA INTELIGENTE)
    // =================================================

    // 1. Pega o elemento dos créditos
    const devCreditsLink = document.getElementById('dev-credits');
    
    // 2. Cria o tooltip dos devs
    const devTooltip = document.createElement('div');
    devTooltip.id = 'dev-tooltip';
    devTooltip.className = 'hidden absolute bg-white border border-slate-300 p-3 rounded-xl shadow-lg max-w-xs text-sm text-slate-700 z-50';
    
    // 3. Define o conteúdo (personalize aqui)
    devTooltip.innerHTML = `
        <strong>Sobre os Desenvolvedores:</strong><br>
        Alunos do 2º Semestre de Ciência de Dados para Negócios da Fatec Sebrae.<br><br>
        <strong>- Felipe Tavares</strong><br>
        <strong>- Thiago Teles</strong><br>
        <strong>- Paulo Futagawa</strong><br>
        <strong>- Thais Nakazone</strong><br>
        <strong>- Riquelme Nichiyama</strong><br><br>

        <strong>Orientadores:</strong><br>
        - Romulo Francisco de Souza Maia<br>
        - Nathane de Castro
    `;
    
    // 4. Adiciona o tooltip à página
    document.body.appendChild(devTooltip);

    // 5. Evento de mouse para o tooltip dos devs
    devCreditsLink.addEventListener('mouseenter', (e) => {
        positionTooltip(devTooltip, e); // Usa a nova função!
    });

    // 6. Evento de mouse para esconder
    devCreditsLink.addEventListener('mouseleave', () => {
        devTooltip.classList.add('hidden');
    });

}); // Fim do 'DOMContentLoaded'


const canvas = document.getElementById('particles');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

let particles = Array.from({length: 40}, () => ({
x: Math.random() * canvas.width,
y: Math.random() * canvas.height,
r: Math.random() * 3 + 1,
dx: (Math.random() - 0.5) * 0.5,
dy: (Math.random() - 0.5) * 0.5
}));

function animate() {
ctx.clearRect(0,0,canvas.width,canvas.height);
ctx.fillStyle = 'rgba(255,255,120,0.3)';
for (const p of particles) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fill();
    p.x += p.dx;
    p.y += p.dy;
    if (p.x < 0 || p.x > canvas.width) p.dx *= -1;
    if (p.y < 0 || p.y > canvas.height) p.dy *= -1;
}
requestAnimationFrame(animate);
}
animate();

// --- FUNÇÃO DO TOUR (MOVIDA PARA CÁ) ---
function startTour() {
    alert('Bem-vindo ao Meta Day! 🎉\n\nUse o chat para tirar dúvidas sobre:\n• Localização dos projetos\n• Horários das palestras\n• Informações gerais do evento');
}