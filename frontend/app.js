// Vernünftiges Logging einrichten
const Logger = {
    info: (msg, data = '') => console.info(`[INFO] ${msg}`, data),
    error: (msg, err) => console.error(`[ERROR] ${msg}`, err),
    debug: (msg, data = '') => console.debug(`[DEBUG] ${msg}`, data)
};

// Absoluter Pfad zum FastAPI-Backend
const API_ENDPOINT = 'http://127.0.0.1:8000/api/v1/chat/message';

document.addEventListener('DOMContentLoaded', () => {
    const ui = {
        container: document.getElementById('chat-messages'),
        input: document.getElementById('user-input'),
        btn: document.getElementById('send-btn'),
        status: document.getElementById('status-indicator'),
        heroSelect: document.getElementById('hero-select')
    };

    // Auto-Resize für die Textarea
    ui.input.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });

    ui.btn.addEventListener('click', sendMessage);
    ui.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    async function sendMessage() {
        const text = ui.input.value.trim();
        const selectedHero = ui.heroSelect.value;
        if (!text) return;

        appendUserMessage(text);
        resetInput();

        const heroDiv = createHeroMessageElement();
        ui.container.appendChild(heroDiv.wrapper);
        scrollToBottom();

        setStreamStatus(true);

        try {
            Logger.info(`Starte SSE Stream zum Council (Port 8000) für: ${selectedHero}`);
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: text,
                    hero_id: selectedHero,
                    stream: true
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            // In frontend/app.js innerhalb der while(true) Schleife von sendMessage():
let currentHeroDiv = null;

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
        if (line.startsWith('data:')) {
            const dataPayload = line.slice(5).trim();
            if (dataPayload === '[DONE]' || dataPayload.includes('"status": "done"')) continue;

            // Wenn ein neuer Agent spricht oder eine Info kommt, neue Blase machen
            if (dataPayload.includes('"status": "starting_agent"')) {
                const info = JSON.parse(dataPayload);
                currentHeroDiv = createHeroMessageElement();

                // Agenten-Namen als Label hinzufügen
                const nameLabel = document.createElement('div');
                nameLabel.style.fontWeight = 'bold';
                nameLabel.style.color = '#7aa2f7';
                nameLabel.style.marginBottom = '5px';
                nameLabel.textContent = info.agent;
                currentHeroDiv.wrapper.prepend(nameLabel);

                ui.container.appendChild(currentHeroDiv.wrapper);
                scrollToBottom();
                continue;
            }

            // System-Infos (z.B. Phasen-Übergänge) anzeigen
            if (dataPayload.includes('"status": "info"')) {
                const info = JSON.parse(dataPayload);
                const infoDiv = document.createElement('div');
                infoDiv.style.textAlign = 'center';
                infoDiv.style.color = '#8c8fa1';
                infoDiv.style.margin = '10px 0';
                infoDiv.textContent = `--- ${info.message} ---`;
                ui.container.appendChild(infoDiv);
                scrollToBottom();
                continue;
            }

            if (currentHeroDiv && !dataPayload.includes('"status": "agent_done"')) {
                const parsedData = parsePartialJson(dataPayload);
                if (parsedData) {
                    // Berücksichtigt VoteResponse (chosen_option_id) und AgentResponse (spoken_text)
                    if (parsedData.chosen_option_id) parsedData.spoken_text = `VOTE: ${parsedData.chosen_option_id}`;
                    updateHeroMessage(currentHeroDiv, parsedData);
                    scrollToBottom();
                }
            }
        }
    }
}
        } catch (error) {
            Logger.error('Stream-Verbindung fehlgeschlagen', error);
            updateHeroMessage(heroDiv, { spoken_text: "Die Verbindung zum Rat wurde unterbrochen." }, true);
        } finally {
            setStreamStatus(false);
        }
    }

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user';
        div.textContent = text;
        ui.container.appendChild(div);
    }

    function createHeroMessageElement() {
        const wrapper = document.createElement('div');
        wrapper.className = 'message hero';

        const monologue = document.createElement('div');
        monologue.className = 'inner-monologue';

        const spoken = document.createElement('div');
        spoken.className = 'spoken-text';

        wrapper.append(monologue, spoken);
        return { wrapper, monologue, spoken };
    }

    function updateHeroMessage(elements, data, isError = false) {
        if (data.inner_monologue !== undefined) {
            elements.monologue.textContent = data.inner_monologue ? `💭 ${data.inner_monologue}` : '';
        }
        if (data.spoken_text !== undefined) {
            elements.spoken.textContent = data.spoken_text;
        }
        if (isError) {
            elements.spoken.classList.add('error-text');
        }
    }

    function parsePartialJson(dataStr) {
        try {
            return JSON.parse(dataStr);
        } catch (e) {
            const extract = (key) => {
                const regex = new RegExp(`"${key}"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)`);
                const match = dataStr.match(regex);
                if (match) {
                    return match[1].replace(/\\"/g, '"').replace(/\\n/g, '\n');
                }
                return undefined;
            };

            return {
                inner_monologue: extract('inner_monologue'),
                spoken_text: extract('spoken_text')
            };
        }
    }

    function resetInput() {
        ui.input.value = '';
        ui.input.style.height = 'auto';
    }

    function scrollToBottom() {
        ui.container.scrollTop = ui.container.scrollHeight;
    }

    function setStreamStatus(isActive) {
        ui.status.classList.toggle('active', isActive);
        ui.btn.disabled = isActive;
        ui.input.disabled = isActive;
        ui.heroSelect.disabled = isActive;
    }
});