const Logger = {
    info: (msg, data = '') => console.info(`[INFO] ${msg}`, data),
    error: (msg, err) => console.error(`[ERROR] ${msg}`, err),
    debug: (msg, data = '') => console.debug(`[DEBUG] ${msg}`, data)
};

const API_ENDPOINT = 'http://127.0.0.1:8000/api/v1/chat/message';

document.addEventListener('DOMContentLoaded', () => {
    const ui = {
        container: document.getElementById('chat-messages'),
        input: document.getElementById('user-input'),
        btn: document.getElementById('send-btn'),
        status: document.getElementById('status-indicator'),
        heroSelect: document.getElementById('hero-select'),
        strategySelect: document.getElementById('strategy-select'),
        autoModCheckbox: document.getElementById('auto-moderator')
    };

    // UI Logic für die Checkbox
    ui.autoModCheckbox.addEventListener('change', (e) => {
        ui.heroSelect.disabled = e.target.checked;
    });

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
        if (!text) return;

        appendUserMessage(text);
        resetInput();
        setStreamStatus(true);

        // Das neue Payload aufbauen!
        const payload = {
            query: text,
            stream: true,
            strategy: ui.strategySelect.value,
            auto_select_agents: ui.autoModCheckbox.checked,
            manual_agents: ui.autoModCheckbox.checked ? [] : [ui.heroSelect.value]
        };

        try {
            Logger.info(`Starte Anfrage an API`, payload);
            const response = await fetch(API_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
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

                        if (dataPayload.includes('"status": "starting_agent"')) {
                            const info = JSON.parse(dataPayload);
                            currentHeroDiv = createHeroMessageElement();

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

                        if (dataPayload.includes('"status": "info"')) {
                            const info = JSON.parse(dataPayload);
                            const infoDiv = document.createElement('div');
                            infoDiv.style.textAlign = 'center';
                            infoDiv.style.color = '#8c8fa1';
                            infoDiv.style.margin = '15px 0';
                            infoDiv.style.whiteSpace = 'pre-line'; // Für Umbrüche im Text
                            infoDiv.textContent = `--- ${info.message} ---`;
                            ui.container.appendChild(infoDiv);
                            scrollToBottom();
                            continue;
                        }

                        // Fehler vom Backend sauber als System-Nachricht rendern
                        if (dataPayload.includes('"status": "error"')) {
                            const errorInfo = JSON.parse(dataPayload);
                            const errDiv = document.createElement('div');
                            errDiv.style.textAlign = 'center';
                            errDiv.style.color = '#f7768e'; // Rote Fehlerfarbe
                            errDiv.style.margin = '15px 0';
                            errDiv.style.fontWeight = 'bold';
                            errDiv.textContent = `⚠️ Systemfehler: ${errorInfo.message}`;
                            ui.container.appendChild(errDiv);
                            scrollToBottom();
                        continue;
                        }

                        if (currentHeroDiv && !dataPayload.includes('"status": "agent_done"')) {
                            const parsedData = parsePartialJson(dataPayload);
                            if (parsedData) {
                                // Spezial-Behandlung für VoteResponse Arrays
                                if (parsedData.votes && Array.isArray(parsedData.votes)) {
                                    let voteText = "";
                                    parsedData.votes.forEach(v => {
                                        if (v.agenda_item) voteText += `📌 ${v.agenda_item}\n`;
                                        if (v.vote !== undefined) {
                                            const decision = v.vote ? '✅ JA' : '❌ NEIN';
                                            voteText += `👉 ${decision} (${v.reason || '...'}) \n\n`;
                                        }
                                    });
                                    parsedData.spoken_text = voteText.trim();
                                }
                                updateHeroMessage(currentHeroDiv, parsedData);
                                scrollToBottom();
                            }
                        }
                    }
                }
            }
        } catch (error) {
            Logger.error('Stream Error', error);
            const errDiv = document.createElement('div');
            errDiv.style.color = '#f7768e';
            errDiv.textContent = 'Verbindung zum Rat unterbrochen: ' + error.message;
            ui.container.appendChild(errDiv);
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
        spoken.style.whiteSpace = 'pre-line';

        wrapper.append(monologue, spoken);
        return { wrapper, monologue, spoken };
    }

    function updateHeroMessage(elements, data) {
        if (data.inner_monologue !== undefined) {
            elements.monologue.textContent = data.inner_monologue ? `💭 ${data.inner_monologue}` : '';
        }
        if (data.spoken_text !== undefined) {
            elements.spoken.textContent = data.spoken_text;
        }
    }

    function parsePartialJson(dataStr) {
        try {
            return JSON.parse(dataStr);
        } catch (e) {
            return null; // Teil-JSON Parsing wird vom Instructor Handle übernommen
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
        ui.strategySelect.disabled = isActive;
        ui.autoModCheckbox.disabled = isActive;
        if (!ui.autoModCheckbox.checked) {
            ui.heroSelect.disabled = isActive;
        }
    }
});